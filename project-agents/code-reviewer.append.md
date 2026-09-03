## Chequeo obligatorio: implementaciones duplicadas y codigo muerto

Antes de cerrar la revision, para cada metodo publico que el diff toque o consuma:

1. **Cuenta sus call sites** con un grep de la OPERACION (`->metodo(`), no del nombre del fichero.
2. **Con control positivo**: el mismo patron aplicado a un metodo hermano que SI se usa. Un
   `0 matches` sin control solo prueba que el grep puede fallar.
3. **Si existen dos implementaciones del mismo metodo en clases distintas**, comprueba que hacen lo
   mismo — mismo endpoint, mismos codigos de estado tratados. Si difieren, es un BLOCKER, no una
   observacion: una de las dos esta mal y nadie sabe cual se ejecuta.

### Por que

REQ-20260825, Phase 6.8. Habia **dos** `reserveAppointment` en dos repositorios:

```
AppointmentsRepository   POST /client/appointments        <- la que usaba la pantalla
MarketplaceRepository    POST /marketplace/appointments   <- la correcta, CERO llamadas
```

`/client/appointments` solo acepta GET. **La reserva de cita nunca habia funcionado**, y el bug era
anterior al ciclo. Ninguna revision lo vio porque cada implementacion, leida por separado, parece
correcta: el defecto solo existe en la comparacion.

Al arreglarlo aparecio ademas que la implementacion usada no trataba el 409, asi que
`SlotConflictException` no se lanzaba nunca y el modal de conflicto de horario era **codigo muerto**
— escrito, probado, y jamas mostrado a nadie.

El orquestador tambien fallo aqui: senalo `marketplace_repository.dart` como el fichero a arreglar
sin comprobar el grafo de llamadas. Era el muerto. Lo detecto el implementador.
