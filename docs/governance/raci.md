# Matriz RACI de operacion y entrega

Esta matriz formaliza responsabilidades de coordinacion a partir de
[team-ownership.md](../sprint-2/team-ownership.md). Es una asignacion operativa;
no atribuye autoria ni revisiones historicas no verificadas.
R = realiza/coordinador; A = responsable de aceptar el resultado;
C = consultado; I = informado. Una persona puede ser R y A en un equipo pequeno.
El profesor evalua la entrega; no se le asigna responsabilidad de operacion.

| Actividad | Juan Camilo Ramon | Felipe Castro Jaimes | Gabriela Sanabria |
|---|---|---|---|
| Contratos y versionado (#19) | R/A | C | C |
| Conectores y acceso a fuentes (#20) | C | R/A | I |
| Discovery, profiling y diccionario (#21) | C | C | R/A |
| Silver y reglas de calidad (#22) | A | C | R |
| Catalogo, linaje y certificacion (#23) | C | C | R/A |
| Orquestacion Airflow (#24) | R/A | C | I |
| API y onboarding (#25) | C | R/A | C |
| Copilot y limites del modelo (#26) | R/A | C | C |
| Interfaz web (#27) | C | C | R/A |
| IaC local y referencia AWS (#28) | C | R/A | I |
| Gold configurable (#31) | R/A | C | C |
| Operacion, migraciones y observabilidad (#32) | A | R | C |
| Benchmark de optimizaciones | A | R | C |
| Evidencia y ensayo multifuente (#29) | A | R | R |
| Presentacion y enlace de entrega | R/A | C | C |

## Responsabilidades sobre los datos

El campo dataset.owner_name identifica al dueno declarado del dataset; no concede
permisos automaticamente. El responsable de gobierno mantiene clasificacion,
diccionario y trazabilidad. Cambios en reglas pasan por revision de contrato;
la propuesta del LLM requiere aprobacion humana. Quien opera verifica el resultado
de la corrida y documenta excepciones antes de certificar. Las credenciales se
mantienen fuera de contratos/Git. La distribucion de acceso real depende del entorno.
