# Regla 21 — Un gate se congela con la prueba de que puede fallar Y pasar

> Propuesta en RETRO-REQ-20260825-registro-cliente-roto (§6); aplicada en la
> Phase 7 de REQ-20260825-mascotas-del-usuario (2026-08-29).

Cinco gates muertos en dos ciclos (REQ-20260822/REQ-20260825): un grep que
daba 0 con el bug intacto (`pushNamed` vs `pushReplacementNamed`), un grep
acotado a 2 ficheros con el defecto en 6, un exit 0 inalcanzable
(`--fatal-infos` ON por defecto + 69 infos), un comando inexistente en el
entorno (phpunit de host, exit 127), y un pipeline de deploy que no corria ni
un test. Todos se escribieron desde la intencion y nunca se ejecutaron.

Antes de congelar CUALQUIER gate (AC de story, comando de fase, check de
pipeline), quien lo redacta pega DOS evidencias:

1. **PUEDE DETECTAR**: ejecutado HOY, con el defecto presente, el gate falla /
   el grep matchea. Si el defecto ya no esta reproducible, se demuestra con un
   control positivo (el patron matchea donde debe).
2. **PUEDE PASAR**: el estado objetivo es alcanzable con el comando tal como
   esta escrito (flags y defaults incluidos — comprobar `--help` si el flag
   tiene default; comprobar que el binario existe en el entorno donde
   correra).

Ampliaciones que la version anterior de esta idea NO cubria:

- Un grep de no-existencia se acota a la OPERACION defectuosa, nunca a un
  nombre que tambien matchea codigo legitimo (el gate `is_active` del
  orquestador habria borrado `services.is_active`).
- Un pipeline de deploy ES un gate: la Phase 6.7 verifica que el workflow
  ejecuta los tests cuyo verde el ciclo reclama (`deploy-backend.yml` corrio
  meses sin uno).
- Complementa la regla 17-T7 (integridad de exit codes): T7 asegura que un
  gate que corre no mienta; esta regla asegura que el gate pueda correr y
  morder.
