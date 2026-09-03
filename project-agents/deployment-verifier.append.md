# deployment-verifier — addendum de proyecto (PetSuite)

> Origen: RETRO-REQ-20260825-registro-cliente-roto (§3); aplicado en la
> Phase 7 de REQ-20260825-mascotas-del-usuario (2026-08-29).

(a) **DEDUP**: un hecho raiz = UN finding; los ficheros afectados son
evidencia del finding, no findings nuevos. Cinco BLOCKER identicos valen
menos que uno bien contado (REQ-20260825: 5 BLOCKER que eran "ficheros del
ciclo sin commitear", contado cinco veces — inflar severidad diluyo el
hallazgo real).

(b) **FIX VALIDADO CONTRA EL ENTORNO DESTINO**: antes de proponer un cambio a
un pipeline de deploy, verifica que cada binario que invocas EXISTE en ese
entorno con esa configuracion de instalacion (`composer --no-dev` ⇒ no hay
require-dev en el servidor). Un fix de deploy no validado es un BLOCKER
disfrazado de solucion: el tuyo habria tumbado todos los jobs con `set -e`
(REQ-20260825). Si los tests no pueden correr en destino, la respuesta es un
job previo en el runner de CI con dependencias dev — exactamente el fix que
se aplico.
