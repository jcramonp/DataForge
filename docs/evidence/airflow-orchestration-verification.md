DAG: olist_alpha_pipeline

Flujo:
source_to_bronze
→ bronze_to_silver
→ silver_quality_gate
→ silver_to_gold

Ejecución exitosa:
manual__2026-08-29T22:37:43.678859+00:00

Resultado:
source_to_bronze       success
bronze_to_silver       success
silver_quality_gate    success
silver_to_gold         success

Pipeline runs registrados:
23–35

Gold final:
112650 input rows
112642 accepted
8 excluded