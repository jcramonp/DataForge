# Verificacion PostgreSQL - optimizaciones aplicadas

Fecha: 2026-10-26. PostgreSQL 16.15 local en Docker.

## Aplicacion en el entorno de la demo

Se ejecuto `python -m src.ops.migrate` contra el control plane existente:
`Applied 1 migration(s); 7 already applied.` La migracion 0008 se registro con
checksum y creo el indice compuesto y la vista materializada. Se ejecuto
`python -m src.ops.refresh_reports`: inicialmente 32 grupos. Ese conteo es un
snapshot y puede cambiar con nuevas corridas; no es el tamano del dataset.
Ver metadata-performance-live.json para la verificacion posterior sobre datos reales.

## Comparativo reproducible

Datos sinteticos: 300.000 dataset_version y 300.000 pipeline_run, 1.000 datasets.
Se usa PostgreSQL real, no un mock. Esquema transaccional aislado eliminado mediante
rollback. No se insertaron filas sinteticas en el catalogo de la demo.
Siete muestras por consulta, cache caliente, misma conexion y mismo conjunto de datos.
Mediana de Execution Time de EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON).
La consulta y sus resultados son identicos antes/despues de cada optimizacion.
La primera conserva el indice simple existente como baseline.
La segunda conserva SQL identico mediante metadata_run_totals: primero es una vista
que agrega las tablas, despues expone la preagregacion materializada equivalente.

| Tecnica | Antes (ms) | Despues (ms) | Relacion antes/despues | Resultados |
|---|---:|---:|---:|---|
| Indice compuesto: ultima version | 0.481 | 0.041 | 11.73x | Iguales |
| Vista materializada: reporte de corridas | 29.743 | 0.078 | 381.32x | Iguales |

## SQL medido

### latest_version_index

```sql
SELECT dataset_version_id, version_label
FROM dataset_version WHERE dataset_id = 42
ORDER BY discovered_at DESC, dataset_version_id DESC LIMIT 1;
```

### materialized_run_totals

```sql
SELECT * FROM metadata_run_totals
WHERE dataset_id = 42 ORDER BY run_type, status;
```

## Costos y limites

Construccion conjunta: 767.526 ms. Refresco del materializado:
421.315 ms en el mismo volumen sintetico. Se pagan espacio y costo
de escritura del indice; el reporte requiere refresco y puede estar desactualizado.
No se usan los tiempos sinteticos como estimacion de latencia en produccion.
La base real de la demo es pequena; no se afirma esa misma aceleracion sobre ella.
No se cambio el overview de la UI para consumir datos potencialmente obsoletos.

La tecnica de particionar Parquet, documentada en performance-partitioning-verification.md,
es evidencia experimental adicional, NO se cuenta como una de estas dos optimizaciones
PostgreSQL ni como almacenamiento productivo ya particionado.

## Evidencia y reproduccion

- [Resultados, muestras y planes completos](metadata-performance-results.json).
- [Aplicacion y comprobacion con datos reales](metadata-performance-live.json).
- [Migracion](../../database/migrations/0008_metadata_performance.sql).
- [Procedimiento y operacion](../operations/metadata-performance.md).

El benchmark reaplica la migracion dos veces y verifica igualdad despues del refresco.
Ver tambien las pruebas de integracion de metadata performance y migraciones.
