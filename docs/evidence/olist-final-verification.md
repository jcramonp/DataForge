# Regresion Olist final - 2026-10-26

Se registro config/examples/olist.yaml por POST /api/onboarding/contracts y se
activo el contrato #13 revision 1. La API acepto una sola ejecucion y se consulto
ese mismo external_run_id hasta su estado terminal.

- Orquestacion persistida: #17, success.
- External run: manual__2026-10-26T19:58:21.090629+00:00.
- Airflow: inicio 19:58:22 UTC, final 20:00:24 UTC.
- Cuatro datasets con Bronze, profiling y Silver; Gold order_items_gold y
  evaluacion de certificacion completos. Se ejecuto modo evaluate, no se
  afirmo una nueva promocion manual a certified.

| Dataset | Bronze | Silver | Cuarentena | Gold |
|---|---:|---:|---:|---:|
| customers | 99.441 | 99.441 | 0 | - |
| orders | 99.441 | 99.441 | 0 | - |
| order_items | 112.650 | 112.650 | 0 | - |
| products | 32.951 | 32.947 | 4 | - |
| order_items_gold | - | - | - | 112.642 |

Hay 9 relaciones de linaje hacia activos producidos por esta corrida.
Las cuatro filas de products se aislaron por reglas criticas. La diferencia
entre Gold y order_items corresponde al resultado de joins sobre Silver;
no debe presentarse como 8 filas enviadas a cuarentena.

[Datos de respuesta, estados y activos persistidos](olist-final-live-run.json).
Los tiempos y conteos corresponden a esta corrida, no a datos de prueba simulados.
