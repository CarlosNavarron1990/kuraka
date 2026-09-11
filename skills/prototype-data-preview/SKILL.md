---
name: prototype-data-preview
description: "Build an interactive HTML prototype that shows BOTH the screen and the database writes it would produce — every table that intervenes, every column, and the real value each would receive as the user operates the mock. Used in the pre-flow conversation (before Phase 1) to let the user validate a solution outline visually, and again whenever a decision hinges on persistence. Its output is a decision artifact, never shipped code."
agent: "orchestrator (the Kuraka itself — a subagent cannot publish artifacts)"
phase: "pre-flow (solution outline) · optional aid to Phase 1 / Phase 3 schema freeze"
disable-model-invocation: false
---

# prototype-data-preview — prototipo interactivo con vista de escritura

> Nace de REQ-20260908-otra-direccion-siniestro. En ese ciclo, un prototipo
> HTML de UI resolvió en tres iteraciones lo que cuatro rondas de
> `AskUserQuestion` no habían cerrado — pero la mitad de las decisiones
> reales (qué se guarda, dónde, y qué NO se toca) seguían siendo invisibles.
> Al añadir la vista de escritura por tabla, el usuario detectó de un vistazo
> que el punto del mapa que la pantalla ya mostraba no aterrizaba en ninguna
> columna. Esa es la clase de hallazgo que esta skill existe para adelantar.

---

## Cuándo se usa

**Se usa cuando la decisión del usuario depende de algo que no se puede leer
en una lista de opciones.** Señales concretas:

- El usuario responde a un `AskUserQuestion` con «no lo entiendo, enséñamelo»,
  o con una corrección que revela que estaba imaginando otro modelo.
- Dos alternativas se distinguen por un **estado invisible** (qué queda en la
  BD, qué se descarta, qué no se sobrescribe), no por lo que se ve en pantalla.
- El outline toca un flujo **con estado**: precarga, modos, limpieza de campos,
  perfiles que alimentan formularios (regla 20, nivel 1 (b)/(c)).
- El schema freeze de Fase 3 tiene que decidir si un dato se persiste o viaja
  suelto en el payload.

**NO se usa** para: pantallas sin decisión pendiente, cambios puramente
mecánicos (restyle, rename, i18n), ni como sustituto del prototipo React/Pencil
canónico del proyecto cuando ya existe uno.

---

## Qué produce

**Un solo fichero `.html` autónomo**, publicado como Artifact y copiado a
`${architecture.paths.docs_process_root}/PROTOTIPO-{YYYYMMDD}-{slug}.html`.

Tiene **dos mitades obligatorias**, lado a lado:

### Mitad izquierda — la pantalla

Réplica fiel del producto, no una maqueta genérica:

- **Toma los tokens de marca del proyecto**, leídos del fichero real
  (`tailwind.config.js`, `main.css`, o el equivalente del stack). Nunca
  inventes una paleta.
- **Copia el markup real** de la pantalla que se modifica: mismas etiquetas,
  mismos mensajes de error, mismos textos de estado. Si el producto dice
  «Ubicación registrada · ±8 m precisión», el prototipo dice eso.
- Es **operable**: el usuario teclea, conmuta, marca. No es un pantallazo.
- Si el producto es de tema fijo (claro u oscuro), la pantalla simulada
  mantiene **sus** tokens en ambos temas del lector, como un dispositivo
  fotografiado. El resto de la página sí sigue el tema del lector.

### Mitad derecha — qué se graba

Una tabla por **cada tabla de BD que interviene**, con:

| Elemento | Regla |
|---|---|
| Nombre de la tabla | el real, en monoespaciada |
| Operación | `INSERT` / `UPDATE` / `SELECT` / `SIN ESCRITURA`, y **cambia en vivo** según el estado del formulario |
| Una fila por columna | nombre real de la columna · **valor real** que recibiría ahora mismo · estado |
| Estado de cada fila | `se escribe` · `no se toca · ya tiene valor` · `no se toca · modo X` · `sin resolver` · `bloquea` |
| Columnas nuevas | marcadas `NUEVA` — las que trae la migración de este ciclo |
| Datos que NO se persisten | fila explícita diciéndolo (p.ej. un flag que viaja en el payload y muere ahí) |

**Las tablas de solo lectura también entran.** Una tabla que gatea el envío
(cobertura, catálogo, permisos) es parte de la explicación aunque no reciba
ninguna escritura.

---

## Reglas duras

1. **Todo valor y todo nombre de columna sale del código real.** Antes de
   escribir el HTML, abre el modelo, el schema y la migración. Un nombre de
   columna inventado convierte el prototipo en desinformación con aspecto de
   evidencia — y el usuario decidirá sobre él (regla 19 R-CUERPO).
2. **Marca lo que NO existe todavía.** Si una columna la trae la migración de
   este ciclo, va con distintivo. Si un campo se envía hoy y el backend lo
   descarta, dilo en el propio prototipo.
3. **La mitad derecha reacciona a la izquierda.** Si el usuario cambia de modo
   y las escrituras no cambian, la mitad derecha es decoración y sobra.
4. **No es código de producción y no se parece a él.** Vive en
   `docs/process/`, es un `.html` suelto sin dependencias más allá de las
   fuentes, y **nunca** se importa desde `src/`.
5. **Se actualiza con cada decisión del usuario, en el sitio.** Republica el
   mismo fichero (misma URL de Artifact) en vez de crear v2, v3, v4: el usuario
   necesita un enlace estable, no una colección.
6. **Sin librerías.** JS plano. Un prototipo que tarda en cargar o que falla
   por un CDN no se usa.
7. **Lo escribe el orquestador**, porque solo él puede publicar Artifacts y
   porque `docs/` es su excepción legítima (ver `kuraka.md` → Orchestrator
   constraint). No delegues esto a un implementador: no es código del producto.

---

## Procedimiento

1. **Reúne las coordenadas** (regla 21 §6 — se generan, no se teclean):
   - `wc -l` y lectura del markup de la pantalla que se toca.
   - modelo(s) SQLAlchemy/ORM de cada tabla implicada: nombres y nullabilidad
     reales de las columnas.
   - el schema de request que decide qué campos se aceptan (y cuáles se
     descartan en silencio).
   - la función que escribe (`create_*`, backfill, repositorio) y **sus
     condiciones** — «solo si está vacío», «nunca sobrescribe», etc., leídas
     del cuerpo, no del docstring.
   - los tokens de marca del proyecto.
2. **Escribe el fichero** en el scratchpad. Carga antes la skill
   `artifact-design`.
3. **Comprueba la sintaxis del script** antes de publicar:
   `node --check` sobre el bloque extraído. Un prototipo roto quema una
   iteración entera del usuario.
4. **Publica** como Artifact, **copia** a `docs/process/` y **envíaselo** al
   usuario (`SendUserFile`, `display: render`).
5. **Itera en el sitio** conforme el usuario corrige el modelo.
6. **Cítalo en el REQ** como referencia visual aprobada, con su ruta.

---

## Salida esperada de la conversación

El prototipo no es el entregable: el entregable son **decisiones cerradas**.
Cuando el usuario deja de corregirlo, tienes:

- el modelo de comportamiento acordado, sin ambigüedad;
- la lista de tablas y columnas que el ciclo toca — que es exactamente el
  inventario que la Fase 3 va a congelar;
- y, con frecuencia, un **bug latente** que nadie buscaba: un dato que la
  interfaz promete y la base de datos nunca recibe.

## Anti-patrones

- ❌ Enseñar la pantalla y omitir las escrituras: deja fuera la mitad que se
  discute en el schema freeze.
- ❌ Nombres de columna aproximados («algo tipo `lat`»). O es el nombre real o
  no se pone.
- ❌ Un prototipo por variante. Un solo fichero con las variantes dentro,
  sincronizadas, para que la comparación sea de un vistazo.
- ❌ Convertirlo en una app. Si necesita router, build o estado global, se te
  fue de las manos: es una ayuda de decisión, no un producto.
