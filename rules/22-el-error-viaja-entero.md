# Regla 22 — El error viaja entero

Cuando una capa recibe un error de otra, **propaga el motivo**. No lo sustituyas por un texto fijo.

Aplica a cualquier frontera: cliente↔servidor, repositorio↔pantalla, servicio↔controlador.

## La regla

1. **Nunca sustituyas el motivo de un error por una cadena literal.** Si el servidor manda
   `{"errors":{"tenant_id":["No estas afiliado a esta clinica."]}}`, eso es lo que tiene que llegar
   al usuario y al log. Un `throw Exception('No se pudo hacer X')` en el `else` de un `if
   (statusCode == 200)` es un borrado de información.

2. **Si no hay cuerpo util, propaga al menos el codigo.** `"No se pudo agendar la cita (codigo 405)"`
   es infinitamente mas util que `"Intenta nuevamente"`, y cuesta lo mismo.

3. **No atribuyas la causa si no la conoces.** «Revisa tu conexion» ante un 422 no solo no ayuda:
   manda a la persona a reiniciar el router por un error de validacion. Reserva el mensaje de red
   para fallos de red reales (`SocketException`, `Connection refused`), y compruebalo, no lo asumas.

4. **Reporta el error a observabilidad con su codigo**, ademas de mostrarlo. El usuario ve un
   mensaje; nosotros necesitamos el rastro.

5. **Cuando haya dos capas, arregla las dos.** Propagar en el repositorio no sirve de nada si la
   pantalla vuelve a tirarlo en su `catch`.

## Por que existe

Cuatro diagnosticos a ciegas en una sola sesion (2026-08-27/29), todos por lo mismo:

| Lo que la app decia | Lo que pasaba |
|---|---|
| «Error al registrar mascota en el servidor» | 409 — falta afiliarse a una clinica |
| «no hay internet» | connection refused: el release apuntaba a `localhost` |
| generico | 422 — no estas afiliado |
| «No se pudo agendar la cita. Intenta nuevamente.» | 405 — la ruta no acepta POST |

En los cuatro el servidor mandaba una explicacion accionable y la app la sustituia. En **dos**, el
texto desorientaba activamente.

El cuarto caso es el que mejor lo ilustra: la reserva de cita **nunca habia funcionado** porque
apuntaba a `POST /client/appointments`, que solo acepta GET. El mensaje generico llevaba tapandolo
desde siempre. Hicieron falta **cinco pasos de diagnostico** para llegar a una causa que el servidor
estaba diciendo desde el principio.

## Como se verifica

Un test por cada rama del manejo de errores, y **cada uno es el control positivo del otro**:

- un 4xx con motivo -> se muestra **ese** motivo;
- un codigo sin cuerpo util -> se muestra el codigo;
- un fallo de red real -> se muestra el mensaje de red.

Sin los tres, una implementacion que muestre siempre lo mismo pasa igual.

## Excepcion

Un mensaje de error **no debe filtrar informacion que el usuario no deberia tener**: existencia de
recursos ajenos, detalles internos de la infraestructura, trazas. Si hay que recortar, recorta hacia
el usuario y **manda el detalle completo a observabilidad**. Recortar en los dos sitios a la vez es
lo que esta regla prohibe.
