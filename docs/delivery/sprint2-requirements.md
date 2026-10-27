# Sprint 2 - matriz de requisitos y evidencia

Criterio: captura de instrucciones del profesor compartida el 26 de octubre de
2026. Se separa cumplimiento tecnico local de los pasos humanos de entrega.
La matriz describe este conjunto de cambios; debe incorporarse a GitHub antes
de entregar el enlace. No equivale a que el profesor ya lo haya aceptado.

| Requisito | Implementacion / evidencia | Estado |
|---|---|---|
| PDF con enlace GitHub | [Presentacion](dataforge-sprint2.pdf), [fuente reproducible](../../scripts/build_sprint2_presentation.py) | Preparado; revisar y publicar en el PR |
| Cambios frente a Sprint 1 | [Changelog](../../CHANGELOG.md), diapositiva comparativa | Documentado |
| Arquitectura actualizada y README | [Arquitectura](../sprint-2/architecture.md), README raiz | Documentado; local vs AWS explicito |
| IaC | docker-compose.yml, Dockerfile, airflow/Dockerfile; [evidencia previa](../evidence/infrastructure-verification.md) | Implementado local; no se afirma IaC AWS |
| Pipelines salvo DataOps/consumo | src/connectors, ingestion, discovery, transformations, quality, orchestration; [Olist final](../evidence/olist-final-verification.md) | Implementados y regresion local exitosa |
| 2 optimizaciones de base de datos aplicadas | [Migracion 0008](../../database/migrations/0008_metadata_performance.sql), [aplicacion real](../evidence/metadata-performance-live.json) | Indice compuesto + vista materializada aplicados |
| Misma consulta antes/despues de cada optimizacion | [Comparativo](../evidence/metadata-performance-verification.md), JSON de planes/muestras | Medido; igualdad exacta; volumen sintetico declarado |
| Diccionario | [Diccionario](../governance/data-dictionary.md) | Olist, Gold y demos; tipos, significado, claves, nulos y clasificacion |
| Catalogo | [Guia](../governance/data-catalog.md), tablas/API/UI | Implementado y documentado |
| Linaje | src/governance/lineage.py, asset_lineage, UI; Olist final: 9 links | Implementado y verificado |
| RACI | [Matriz](../governance/raci.md) | Responsabilidad operativa formalizada; no inventa autoria historica |
| Reglas de calidad | Contratos, src/quality, quality_result; [motor](../evidence/silver-quality-engine-verification.md) | Implementadas; cuarentena real en CSV, REST y Olist |
| Demo captura-limpieza-almacenamiento | [Guion](sprint2-demo-script.md); [Olist](../evidence/olist-final-verification.md); [CSV](../evidence/demo-stability-verification.md) | Ensayo tecnico exitoso; presentar en vivo |
| Problemas y soluciones | PDF y guion; [estabilidad](../evidence/demo-stability-verification.md) | Documentados con limites |
| Conocimientos del curso, otras materias y autonomos | PDF, diapositiva de conceptos aplicados | Mapeo tecnico preparado; el equipo valida nombres exactos de sus materias |

## Pendientes para entregar

1. Aplicar estos cambios al checkout principal, revisar el diff, commit/push/PR,
   esperar CI e integrar en la rama que recibira el profesor.
2. Abrir el PDF final y ensayar el guion con los servicios activos.
3. Confirmar que el profesor tiene acceso al repositorio privado. Un enlace no
   concede acceso; no se cambia visibilidad ni se invita a nadie sin indicacion.
4. El repositorio tiene main como rama predeterminada y esta entrega se prepara
   sobre develop. Enlazar develop explicitamente o integrar la version de entrega
   segun el flujo del equipo; no mezclar ramas sin revision.
5. Validar oralmente la distribucion RACI y los nombres de las otras materias.
   No se atribuyen experiencias personales ni aprobaciones inexistentes.

El texto del profesor no exige AWS expresamente. Si existe otra instruccion que
lo exige, el despliegue AWS sigue pendiente: la referencia no cuenta como desplegado.
No se cierran automaticamente issues del backlog ni se confunde entrega academica
con finalizacion de todas las funcionalidades del producto.

## Verificacion de este conjunto de cambios

- Suite Python previa a las dos pruebas nuevas: 349 casos, 35 omitidos por
  integracion, sin fallos (314 ejecutados satisfactoriamente).
- Dos nuevas pruebas PostgreSQL ejecutadas explicitamente: ambas pasan;
  no utilizan los reset_database/reset_buckets del resto de la suite de integracion.
- Ruff sobre todo el checkout: pasa. git diff --check: pasa.
- Migracion 0008 aplicada; --status confirma 0001 a 0008 registradas.
- PDF: 13 paginas renderizadas e inspeccionadas; enlaces relativos nuevos verificados.
- Frontend sin cambios en esta entrega; las 15 pruebas y el build ya pasaron
  en la verificacion primaria de estabilidad documentada en su evidencia.
- CI remoto del nuevo PR permanece pendiente; no se presenta como ejecutado.

Para reconstruir la presentacion: instalar requirements-presentation.txt y ejecutar
`python scripts/build_sprint2_presentation.py` desde el repositorio. El script lee
los JSON de evidencia; no necesita credenciales ni consultas a los servicios.
