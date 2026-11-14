## Errores típicos generales (los que ya se colaron en proyectos Kuraka; míralos solo si aplican a lo tocado)

CRÍTICOS (bloquean):
- Datos de un cliente concreto en código, fixtures o textos de un producto multi-cliente: lo que cambia por cliente va en configuración.
- Secretos, URLs o claves de producción en el código; tests que llaman a servicios reales.
- Setting de seguridad con valor por defecto vacío: si falta, el control queda apagado sin avisar. Tiene que fallar al arrancar (y mirar el otro lado: frontend, proxy, otro servicio).
- Renombrar una columna de BD sin columna nueva + migración. Migraciones que pisan otra cabeza o numeración frente a la base actual.
- Contrato roto entre piezas: un campo que el productor deja de mandar y el consumidor sigue leyendo (o al revés), nombres de campo inventados. Recorrer el dato productor → BD → consumidor.

DOMINIO Y LÓGICA:
- Valores límite sin test: 0, vacío, null, códigos especiales, zona horaria y cambio de hora, paginación, reintentos sin fin, idempotencia.
- Decidir con el texto, el formato o el orden de un mensaje de un tercero: si ese texto cambia mañana, ¿qué pasa?
- Escritura completa de un JSON que pisa un merge parcial hecho en otro sitio; un merge parcial que no borra las claves que dejan de aplicar.
- Retorno temprano que se salta el resto de un lote mixto (test con un elemento de cada tipo).
- Al borrar código, settings, flags o columnas, lo que solo él leía se queda sin consumidor; una pieza nueva que nadie llama no está terminada.
- Avisos deduplicados de por vida o contadores que un atacante puede agotar: se limitan por tiempo.
- Interruptores por entorno: lo que se dispara al desplegar (sincronizaciones, jobs, datos reales).
- Un camino de error nuevo que depende de estado: ¿qué escrituras durables ya ocurrieron antes de lanzar el error? Un guard que puede rechazar va antes de cualquier paso irreversible.

TESTS:
- Tests que prueban lo supuesto y no la fuente: cada campo externo contra su documentación.
- El test mockea el error con el nombre correcto y el mapeo real falla: usar la función real.
- Haz al menos una mutación del arreglo principal: si ningún test cae, el test no protege nada.
- La BD de test distinta de la real (SQLite frente a Postgres): lo que vale es la real.
- Un test que mockea la unidad que cambia no da señal de regresión.

PR:
- «Atendido» sin que los commits toquen los ficheros del punto.
- Ficheros generados o con solo cambios de fin de línea colados en el diff.
- PR sin clave de tarea en título, rama o commits; PR apilada sobre una rama ya fusionada; varias merge-base (GitHub ve conflictos que el merge local no).
