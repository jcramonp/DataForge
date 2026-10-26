# Optimizaciones PostgreSQL y reporte operativo

La migracion 0008 aplica dos tecnicas diferentes:

1. Indice B-tree compuesto (dataset_id, discovered_at DESC, dataset_version_id DESC).
   Resuelve filtro y orden de la ultima version, patron usado por catalogo y certificacion.
   Agrega costo de escritura y almacenamiento; no reemplaza la clave primaria.
2. Vista materializada metadata_run_totals_cache: preagrega conteos/filas por
   dataset, tipo de corrida y estado. metadata_run_totals expone ese snapshot
   para reportes operativos SQL. Reduce lectura repetida a costa de refresco y espacio.

```powershell
python -m src.ops.migrate
python -m src.ops.refresh_reports
python -m src.performance.benchmark_metadata --rows 300000 --repetitions 7 --output docs/evidence/metadata-performance-results.json
```

```sql
SELECT * FROM metadata_run_totals WHERE dataset_id = 42 ORDER BY run_type, status;
```

El snapshot se llena al crear la vista. Refrescar despues de un lote de corridas
antes de reportar. El comando usa CONCURRENTLY con indice unico; las lecturas
pueden continuar. No hay refresco automatico ni SLA de frescura. El overview de la
UI usa las tablas vivas y conserva su semantica. No usar este reporte para
decidir si una corrida acaba de terminar.

El benchmark crea tablas sinteticas en un esquema unico dentro de una transaccion,
conserva el indice simple previo, mide las mismas dos consultas antes/despues y
comprueba igualdad exacta. Incluye planes EXPLAIN ANALYZE BUFFERS, siete muestras,
mediana, calentamiento, costo de construccion/refresco e idempotencia. Revierte todo
el esquema al terminar o fallar. No desactiva indexes ni altera tablas de la demo.
Los tiempos son evidencia local sobre volumen sintetico; no son una promesa para AWS.
Ver [resultados y aplicacion real](../evidence/metadata-performance-verification.md).
