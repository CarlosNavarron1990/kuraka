# story-refiner — addendum de proyecto (PetSuite)

> Origen: RETRO-REQ-20260825-registro-cliente-roto (§3); aplicado en la
> Phase 7 de REQ-20260825-mascotas-del-usuario (2026-08-29).

1. **Renames con inventario completo.** Un AC que renombra un identificador
   (bundle id, package, clase, columna) DEBE llevar el inventario completo de
   sitios obtenido por grep, pegado en la story. Un rename con inventario
   incompleto deja el sistema en estado intermedio peor que no renombrar
   (CRIT-2, REQ-20260822: el rename real de iOS eran 3 sitios, la story listo
   1 → delta de revert de 59.634 tokens).

2. **Tests colaterales.** Toda story con lista cerrada de ficheros incluye
   una subseccion "Tests colaterales que podrian requerir ajuste" (evidencia:
   S3 de REQ-20260825, 1.84x tool_uses por un revert de label que rompia 2
   tests fuera de la lista cerrada).

3. **Valores de columnas ENUM.** Antes de escribir en un AC un literal para
   una columna que pueda ser ENUM de DB, verifica los valores permitidos en
   la migracion/dump y pega la evidencia. Un literal fuera del ENUM pasa en
   el sqlite de test (no valida ENUM) y falla en MariaDB strict en produccion
   (S8 de REQ-20260825-mascotas: `source: 'app_explicit'` no existia en el
   ENUM `('qr_scan','app_organic','in_clinic')`; lo detuvo el implementador,
   no ningun test).
