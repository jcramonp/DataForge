# Catalogo de datos y guia de consulta

El catalogo operativo esta implementado en PostgreSQL y se consulta mediante la
API y las pantallas Sources, Datasets, Assets y Lineage/Governance. No depende de
un servicio externo de catalogacion. El inventario cambia con cada corrida;
esta guia documenta como consultar su estado real.

| Informacion | Fuente persistida | Consulta / pantalla |
|---|---|---|
| Cliente, proyecto y fuente | client, project, data_source | /api/clients, /api/projects, /api/sources |
| Definicion, dueno, clasificacion | dataset, configuration_contract | /api/datasets, Source Onboarding |
| Esquema, claves y reglas | contrato activo JSON | /api/onboarding/contracts/{cliente}/{proyecto}/{fuente} |
| Version y checksum | dataset_version | detalles de activos y metadatos SQL |
| Perfilado | profiling_result (perfil de columnas en profile_json) | Datasets/Profiling; validar nombres fisicos en migracion 0005 |
| Ubicacion y filas | data_asset | /api/assets, Data Assets |
| Calidad por regla | quality_result | Quality/Quarantine |
| Dependencias | asset_lineage | Lineage/Governance |
| Estado y auditoria | dataset_certification, certification_transition | Lineage/Governance |
| Ejecuciones | pipeline_run, orchestration_run, orchestration_task_run | Pipelines/Runs |

Las rutas exactas y parametros estan en /docs y /openapi.json de la API. Usar
siempre cliente, proyecto y fuente: dataset_code por si solo no es identidad global.
Los nombres fisicos autoritativos son las migraciones, no las etiquetas de la UI.

## Inventario demostrado

| Ambito | Dataset | Proposito | Clasificacion |
|---|---|---|---|
| olist / olist-alpha / olist-csv | customers, orders, order_items, products | Caso comercial Olist | internal; columnas sensibles confidential |
| Mismo contrato Olist | order_items_gold | Integracion por joins y total por item | hereda contexto del contrato; revisar antes de publicar |
| demo-profesor / multifuente / tareas-rest | tareas | Prueba REST JSONPlaceholder /todos | Datos de demostracion |
| demo-profesor / multifuente / ventas-csv | ventas | CSV de seis ventas con dos errores deliberados | Datos sinteticos de demostracion |
| ci-retail / ci-retail-e2e / ci-retail-csv | orders, orders_by_status | Regresion de agregacion Gold | Datos de prueba |

## Consulta SQL de activos

```sql
SELECT c.client_code, p.project_code, ds.source_code, d.dataset_code,
       d.owner_name, d.classification, dv.version_label,
       a.asset_id, a.layer, a.storage_uri, a.row_count
FROM client c
JOIN project p ON p.client_id = c.client_id
JOIN data_source ds ON ds.project_id = p.project_id
JOIN dataset d ON d.source_id = ds.source_id
JOIN dataset_version dv ON dv.dataset_id = d.dataset_id
JOIN pipeline_run r ON r.dataset_version_id = dv.dataset_version_id
JOIN data_asset a ON a.run_id = r.run_id
ORDER BY a.asset_id DESC;
```

Los activos son historicos; no sumar versiones como si fueran filas unicas.
Las URI s3:// identifican objetos; no son enlaces publicos. La clasificacion es
metadato declarado y no implica cifrado, anonimizado ni una politica de acceso aplicada.
Ver [diccionario](data-dictionary.md), [RACI](raci.md) y [modelo](../data-model/alpha-data-model.md).
