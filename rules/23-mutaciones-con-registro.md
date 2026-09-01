# Regla 23 — Mutaciones con registro y restauracion garantizada

La verificacion por mutacion —romper una proteccion, confirmar que su test se pone rojo,
restaurarla— es la unica forma de saber si un test protege algo. Esta regla es sobre **no dejar el
arbol roto al hacerla**.

## La regla

1. **Restaura con `git checkout --`, no con una copia en `/tmp`.** Una copia depende de que el
   comando termine. `git checkout` no depende de nada: el estado limpio ya esta en el indice.

2. **Comprueba el arbol despues de mutar**, siempre, con `git status --porcelain` o `git diff`. La
   restauracion no se da por hecha: se verifica.

3. **Marca la mutacion en el codigo** con un comentario reconocible (`// MUTADO`) y cierra el ciclo
   con un `grep -rn "MUTADO"` sobre el arbol. Un 0 es la prueba de que restauraste; sin marca no hay
   forma barata de saberlo.

4. **Antes de interpretar cualquier resultado inesperado, comprueba que el codigo bajo prueba es el
   original.** Es el primer paso, no el ultimo.

5. **Si te interrumpen a mitad, la restauracion es lo primero al retomar**, antes de responder nada.

## Por que existe

El 2026-08-28 quedo `'species': 'Perro', // MUTADO` en `pet_form_step1_screen.dart` tras una
mutacion interrumpida por el usuario: el comando encadenaba mutar → probar → restaurar, y la
interrupcion se llevo por delante el ultimo paso.

Lo que vino despues es la parte cara. Las ejecuciones siguientes del test devolvian `perro`, y en
vez de sospechar del propio cambio se formularon **dos hipotesis sobre la aplicacion** —el teclado
desplazando el toque, el `State` recreandose entre pasos—. Ambas se descartaron probandolas, que
esta bien, pero **nunca se comprobo lo primero: si el codigo bajo prueba seguia siendo el
original**.

Coste: varias iteraciones de depuracion, y un fallo reportado al usuario **como defecto de su
producto cuando no existia**. La comparacion en base de datos lo dejo claro despues:

```
id 43  27 ago 00:25  species: Perro   <- con la mutacion activa
id 44  28 ago 19:16  species: Gato    <- tras restaurarla
```

Mismos datos en todo lo demas. La funcionalidad siempre habia funcionado.

## Corolario, que es la parte general

**Un resultado raro obliga a dudar del entorno antes que del codigo ajeno.** Arbol sucio, cache,
version desplegada, dato de prueba mal elegido. Todos son mas probables que un bug que ha
sobrevivido a los tests, y todos se descartan en segundos.

En esa misma sesion, una reproduccion fallo por usar una clinica en estado `blocked` — el dato de
prueba, no el codigo. Se detecto rapido porque se leyo el error en vez de teorizar.
